<template>
  <div>Starting example!</div>
</template>

<script>
export default {
  async asyncData({ app }) {
    const response = await app.$client.get(
      'upub/starting/'
    )
    return response.data
  },
  head() {
    return {
      title: this.title,
    }
  },
}
</script>
