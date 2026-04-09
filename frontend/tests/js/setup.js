import { vi } from 'vitest';

globalThis.CSRF_TOKEN = 'test-csrf-token';
globalThis.bootstrap = {
  Modal: class {
    constructor() {
      this.show = vi.fn();
      this.hide = vi.fn();
    }
  },
};

globalThis.fetch = vi.fn(() =>
  Promise.resolve({
    ok: true,
    json: async () => [],
  })
);
