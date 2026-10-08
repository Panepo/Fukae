<script setup>
import { computed, ref } from 'vue'

const props = defineProps({
  heading: { type: String, required: true },
  directory: { type: String, required: true },
  files: { type: Array, required: true },
  formatSize: { type: Function, required: true },
  formatModified: { type: Function, required: true },
})

const emit = defineEmits(['download'])
const sortKey = ref('name')
const sortDirection = ref('asc')

const sortedFiles = computed(() => [...props.files].sort((left, right) => {
  const leftValue = sortKey.value === 'name' ? left.name : Number(left[sortKey.value])
  const rightValue = sortKey.value === 'name' ? right.name : Number(right[sortKey.value])
  const comparison = typeof leftValue === 'string'
    ? leftValue.localeCompare(rightValue)
    : leftValue - rightValue
  return sortDirection.value === 'asc' ? comparison : -comparison
}))

function sortBy(column) {
  if (sortKey.value === column) {
    sortDirection.value = sortDirection.value === 'asc' ? 'desc' : 'asc'
    return
  }

  sortKey.value = column
  sortDirection.value = 'asc'
}

function ariaSort(column) {
  if (sortKey.value !== column) return 'none'
  return sortDirection.value === 'asc' ? 'ascending' : 'descending'
}
</script>

<template>
  <section class="file-group">
    <h3>{{ heading }}</h3>
    <p v-if="!files.length" class="message">No files available.</p>
    <div v-else class="table-wrap">
      <table>
        <thead>
          <tr>
            <th :aria-sort="ariaSort('name')" scope="col"><button class="sort-button" type="button" @click="sortBy('name')">Name <span v-if="sortKey === 'name'">{{ sortDirection }}</span></button></th>
            <th :aria-sort="ariaSort('size')" scope="col"><button class="sort-button" type="button" @click="sortBy('size')">Size <span v-if="sortKey === 'size'">{{ sortDirection }}</span></button></th>
            <th :aria-sort="ariaSort('modified')" scope="col"><button class="sort-button" type="button" @click="sortBy('modified')">Modified <span v-if="sortKey === 'modified'">{{ sortDirection }}</span></button></th>
            <th scope="col">Action</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="file in sortedFiles" :key="file.name">
            <td>{{ file.name }}</td>
            <td>{{ formatSize(file.size) }}</td>
            <td>{{ formatModified(file.modified) }}</td>
            <td><button class="link-button" type="button" @click="emit('download', directory, file.name)">Download</button></td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>
</template>
