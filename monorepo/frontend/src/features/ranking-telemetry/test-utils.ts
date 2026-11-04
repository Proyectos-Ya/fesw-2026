import { vi } from "vitest";

interface ObserverRecord {
  callback: IntersectionObserverCallback;
  elements: Set<Element>;
  disconnected: boolean;
  observer: IntersectionObserver;
}

export interface FakeIntersectionControls {
  /** Informa que `el` está a la vista en la proporción `ratio` (0.6 por defecto). */
  show: (el: Element, ratio?: number) => void;
  /** Informa que `el` salió de la vista. */
  hide: (el: Element) => void;
}

/**
 * Reemplaza `IntersectionObserver` por un doble que se maneja a mano: jsdom no lo
 * tiene. Hay que llamar a `vi.unstubAllGlobals()` al terminar el test.
 */
export function installFakeIntersectionObserver(): FakeIntersectionControls {
  const records: ObserverRecord[] = [];

  class FakeIntersectionObserver {
    private readonly record: ObserverRecord;

    constructor(callback: IntersectionObserverCallback) {
      this.record = {
        callback,
        elements: new Set<Element>(),
        disconnected: false,
        observer: this as unknown as IntersectionObserver,
      };
      records.push(this.record);
    }

    observe(el: Element): void {
      this.record.elements.add(el);
    }

    unobserve(el: Element): void {
      this.record.elements.delete(el);
    }

    disconnect(): void {
      this.record.disconnected = true;
      this.record.elements.clear();
    }

    takeRecords(): IntersectionObserverEntry[] {
      return [];
    }
  }

  vi.stubGlobal("IntersectionObserver", FakeIntersectionObserver);

  function notify(el: Element, ratio: number): void {
    const rect = el.getBoundingClientRect();
    const entry = {
      target: el,
      isIntersecting: ratio > 0,
      intersectionRatio: ratio,
      time: 0,
      boundingClientRect: rect,
      intersectionRect: rect,
      rootBounds: null,
    } as IntersectionObserverEntry;
    for (const record of records) {
      if (record.disconnected || !record.elements.has(el)) continue;
      record.callback([entry], record.observer);
    }
  }

  return {
    show: (el, ratio = 0.6) => notify(el, ratio),
    hide: (el) => notify(el, 0),
  };
}
