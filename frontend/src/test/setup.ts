import '@testing-library/jest-dom'

global.ResizeObserver = class {
  observe() {}
  unobserve() {}
  disconnect() {}
}
global.requestAnimationFrame = (cb: FrameRequestCallback) => setTimeout(cb, 0) as unknown as number
