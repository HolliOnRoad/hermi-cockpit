import { useEffect } from 'react'

interface FileMeta {
  name: string
  type: string
  size: number
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

export function useDragDropGuard() {
  useEffect(() => {
    function onDragOver(e: DragEvent) {
      e.preventDefault()
      e.stopPropagation()
      if (e.dataTransfer) {
        e.dataTransfer.dropEffect = 'none'
      }
    }

    function onDrop(e: DragEvent) {
      e.preventDefault()
      e.stopPropagation()

      const files = e.dataTransfer?.files
      if (!files || files.length === 0) return

      const dropped: FileMeta[] = []
      for (let i = 0; i < files.length; i++) {
        dropped.push({
          name: files[i].name,
          type: files[i].type || 'unknown',
          size: files[i].size,
        })
      }

      console.info(
        `%c[DnD Guard] %c${dropped.length} file(s) dropped — not uploaded`,
        'color: #93c5fd; font-weight: bold',
        'color: #9ca3af',
      )
      console.table(
        dropped.map(f => ({
          Name: f.name,
          Type: f.type,
          Size: formatSize(f.size),
        })),
      )
    }

    document.addEventListener('dragover', onDragOver)
    document.addEventListener('drop', onDrop)

    return () => {
      document.removeEventListener('dragover', onDragOver)
      document.removeEventListener('drop', onDrop)
    }
  }, [])
}
