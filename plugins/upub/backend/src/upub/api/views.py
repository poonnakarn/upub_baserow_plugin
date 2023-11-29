from rest_framework.views import APIView
from rest_framework.response import Response
from django.http import HttpResponse
from rest_framework.permissions import AllowAny

from baserow.api.pagination import PageNumberPagination
from baserow.contrib.database.table.models import Table
from baserow.contrib.database.table.handler import TableHandler
from baserow.contrib.database.api.utils import get_include_exclude_fields
from baserow.contrib.database.api.rows.serializers import (
    get_row_serializer_class,
    RowSerializer,
)

from collections import OrderedDict
from openpyxl.drawing.image import Image
from openpyxl.utils import get_column_letter
from PIL import Image as PILImage
import ast
import io
import pandas as pd
import requests


class ExportExcelView(APIView):
    permission_classes = (AllowAny,)

    def extract_data(self, data_list):
        extracted_info = []
        for item in data_list:
            item_info = {}
            for key, value in item.items():
                if key == "images":  # Special handling for 'images' key
                    item_info[key] = [
                        image_dict["url"] for image_dict in value if "url" in image_dict
                    ]
                elif isinstance(value, OrderedDict):
                    item_info[key] = value.get("value", None)
                elif (
                    isinstance(value, list)
                    and value
                    and isinstance(value[0], OrderedDict)
                ):
                    item_info[key] = value[0].get("value", None)
                else:
                    item_info[key] = value
            extracted_info.append(item_info)
        return extracted_info

    def compress_image(self, image_stream, max_width, max_height, quality=85):
        """
        Compress and resize an image.
        :param image_stream: Input image stream (bytes).
        :param max_width: Maximum width of the output image.
        :param max_height: Maximum height of the output image.
        :param quality: Quality of the output JPEG image (1-100).
        :return: BytesIO stream of the processed image.
        """
        with PILImage.open(image_stream) as img:
            # Resize the image
            img.thumbnail((max_width, max_height))

            # Compress and save the image to a BytesIO stream
            output_stream = io.BytesIO()
            img.save(output_stream, format="JPEG", quality=quality)
            output_stream.seek(0)

            return output_stream

    def get(self, request, pk):
        table = TableHandler().get_table(pk)

        fields = get_include_exclude_fields(table, None, None, user_field_names=True)

        model = table.get_model(
            fields=fields,
            field_ids=[] if fields else None,
        )
        queryset = model.objects.all().enhance_by_fields()

        # paginator = PageNumberPagination()
        # page = paginator.paginate_queryset(queryset, request, self)
        serializer_class = get_row_serializer_class(
            model, RowSerializer, is_response=True, user_field_names=True
        )
        serializer = serializer_class(queryset, many=True)

        extracted_data = self.extract_data(serializer.data)

        df = pd.DataFrame(extracted_data)
        df["title"] = df["generic_name"]
        df = df.drop(
            columns=[
                "id",
                "order",
                "Image_URL1",
                "Image_URL2",
                "cat_level1",
                "cat_level2",
                "cat_level3",
                "cat_level4",
            ]
        )

        # Group by 'generic_name' which is the same as 'title'
        grouped = df.groupby("title")

        final_df = pd.DataFrame()

        for name, group in grouped:
            # DataFrame 1
            trade_names = group["trade_name"].unique()
            df1 = pd.DataFrame(
                {
                    "title": [name] + [""] * (len(trade_names) - 1),
                    "Generic Name (TRADE NAME)": [f"{name} ({', '.join(trade_names)})"]
                    + [""] * (len(trade_names) - 1),
                    "Trade_Name(s)": trade_names,
                    "Generic Trade Name [[^Generic (TRADE NAME) Index^]]": [
                        f"{name} ({', '.join(trade_names)})"
                    ]
                    + [""] * (len(trade_names) - 1),
                    "Trade Name Index[[^Trade Name Index^]]": trade_names,
                }
            )

            # DataFrame 2
            df2 = pd.DataFrame(
                {
                    "ราคาและเงื่อนไข (Price and Prescription Condition):;Trade Name": group[
                        "trade_name"
                    ],
                    "ราคาและเงื่อนไข (Price and Prescription Condition):;Dosage Form": group[
                        "dosage_form"
                    ],
                    "ราคาและเงื่อนไข (Price and Prescription Condition):;Strength or Package Size": group[
                        "strength_package_size"
                    ],
                    "ราคาและเงื่อนไข (Price and Prescription Condition):;ราคาขาย": group[
                        "price"
                    ],
                    "ราคาและเงื่อนไข (Price and Prescription Condition):;บัญชียาหลักแห่งชาติ": group[
                        "national_list"
                    ],
                    "ราคาและเงื่อนไข_(Price_and_Prescription_Condition):;เงื่อนไขการสั่งยา/หมายเหตุ": group[
                        "remarks"
                    ],
                }
            )

            # DataFrame 3
            cat_labels = (
                group[
                    [
                        "cat_level1_label",
                        "cat_level2_label",
                        "cat_level3_label",
                        "cat_level4_label",
                    ]
                ]
                .iloc[0]
                .tolist()
            )
            # Remove empty lists and None values
            cat_labels = [label for label in cat_labels if label and label != "[]"]
            df3 = pd.DataFrame(
                {
                    "Drug_class:;numeral": range(1, len(cat_labels) + 1),
                    "Drug Class:;class": cat_labels,
                }
            )

            # DataFrame 4
            df4_data = []
            for _, row in group.iterrows():
                # Safely evaluate the 'images' column if it's a string representation of a list
                images = (
                    ast.literal_eval(row["images"])
                    if isinstance(row["images"], str)
                    else row["images"]
                )
                images = images if isinstance(images, list) else [images]

                trade_name_and_dosage = f"{row['trade_name']} {row['dosage_form']} ({row['strength_package_size']})"
                for img_url in images:
                    if pd.notna(img_url):
                        df4_data.append(
                            {
                                "ตารางยาและรูปภาพ:;Trade_Dosage": trade_name_and_dosage,
                                "ตารางยาและรูปภาพ:;Image": img_url,
                            }
                        )

            df4 = pd.DataFrame(df4_data)

            df1 = df1.reset_index(drop=True)
            df2 = df2.reset_index(drop=True)
            df3 = df3.reset_index(drop=True)
            df4 = df4.reset_index(drop=True)

            # Combine df1 and df2
            combined_df = pd.concat([df1, df3, df2, df4], axis=1).fillna("")

            # Append to the final DataFrame
            final_df = pd.concat([final_df, combined_df], axis=0).fillna("")

        # Reset index of the final DataFrame
        final_df.reset_index(drop=True, inplace=True)

        final_df["ตารางยาและรูปภาพ:;Image"] = final_df[
            "ตารางยาและรูปภาพ:;Image"
        ].replace(to_replace=r"http://localhost:4000", value="http://caddy", regex=True)

        # Create a BytesIO buffer to hold the Excel file
        excel_buffer = io.BytesIO()

        # Use Pandas ExcelWriter to write to the buffer
        with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
            final_df.to_excel(writer, index=False)
            worksheet = writer.sheets["Sheet1"]

            # Find the column index for the 'images' column
            image_col_idx = (
                final_df.columns.get_loc("ตารางยาและรูปภาพ:;Image") + 1
            )  # +1 because Excel columns are 1-indexed
            image_col_letter = get_column_letter(image_col_idx)

            for idx, row in final_df.iterrows():
                image = row["ตารางยาและรูปภาพ:;Image"]

                # Clear the image URL from the cell after inserting the image
                worksheet[f"{image_col_letter}{idx + 2}"].value = ""

                if image:
                    img_url = image
                    response = requests.get(img_url)
                    if response.status_code == 200:
                        image_stream = io.BytesIO(response.content)
                        compressed_image_stream = self.compress_image(
                            image_stream, max_width=512, max_height=384, quality=85
                        )
                        img = Image(compressed_image_stream)
                        cell_location = f"{image_col_letter}{idx + 2}"  # Place the image in the 'image' column
                        worksheet.add_image(img, cell_location)

                        pixels_to_points = 0.75  # This is an approximation, you may need to adjust this factor
                        image_height_in_points = img.height * pixels_to_points
                        worksheet.row_dimensions[
                            idx + 2
                        ].height = image_height_in_points

        # Set the pointer of the buffer to the beginning
        excel_buffer.seek(0)

        # Create an HTTP response with the Excel file as content
        response = HttpResponse(
            excel_buffer.read(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = 'attachment; filename="formulary.xlsx"'

        return response
