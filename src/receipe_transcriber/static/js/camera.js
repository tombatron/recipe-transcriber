// Simple camera module for capturing recipe images
window.camera = {
  stream: null,
  
  async start() {
    try {
      this.stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: 'environment' }
      })
      
      const video = document.getElementById('camera-video')
      video.srcObject = this.stream
      
      document.getElementById('camera-modal').classList.remove('hidden')
    } catch (error) {
      console.error('Camera access error:', error)
      alert('Unable to access camera. Please check permissions.')
    }
  },
  
  close() {
    if (this.stream) {
      this.stream.getTracks().forEach(track => track.stop())
      this.stream = null
    }
    
    document.getElementById('camera-modal').classList.add('hidden')
  },
  
  async capture() {
    const video = document.getElementById('camera-video')
    const canvas = document.getElementById('camera-canvas')
    
    canvas.width = video.videoWidth
    canvas.height = video.videoHeight
    
    const ctx = canvas.getContext('2d')
    ctx.drawImage(video, 0, 0)
    
    canvas.toBlob(async (blob) => {
      this.close()
      
      const formData = new FormData()
      formData.append('images', blob, 'camera-capture.jpg')
      
      try {
        const response = await fetch('/upload', {
          method: 'POST',
          body: formData
        })
        
        if (response.ok) {
          const html = await response.text()
          // Prepend to processing items container
          const processingItems = document.getElementById('processing-items')
          if (processingItems) {
            processingItems.insertAdjacentHTML('afterbegin', html)
          }
          // Update header visibility if helper exists
          if (typeof window.updateProcessingVisibility === 'function') {
            window.updateProcessingVisibility()
          }
        } else {
          alert('Upload failed. Please try again.')
        }
      } catch (error) {
        console.error('Upload error:', error)
        alert('Upload failed. Please try again.')
      }
    }, 'image/jpeg', 0.9)
  }
}
