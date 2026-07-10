/**
 * HourlyRateLimiter — soatiga N ta amalga ruxsat beruvchi navbat (queue).
 * Instagram DM uchun ~200 xabar/soat cheklovidan himoya qiladi.
 *
 * Sliding-window: oxirgi 1 soatdagi yuborishlar sanaladi; limitga yetganda
 * eng eski yozuv oynadan chiqguncha kutiladi. Amallar ketma-ket bajariladi.
 */
export class HourlyRateLimiter {
  private timestamps: number[] = [];
  private queue: Array<() => void> = [];
  private processing = false;

  constructor(
    private readonly limit: number,
    private readonly windowMs: number = 60 * 60 * 1000,
  ) {}

  schedule<T>(task: () => Promise<T>): Promise<T> {
    return new Promise<T>((resolve, reject) => {
      this.queue.push(() => {
        task().then(resolve, reject);
      });
      void this.process();
    });
  }

  private async process(): Promise<void> {
    if (this.processing) return;
    this.processing = true;
    try {
      while (this.queue.length > 0) {
        const now = Date.now();
        this.timestamps = this.timestamps.filter((t) => now - t < this.windowMs);
        if (this.timestamps.length >= this.limit) {
          const oldest = this.timestamps[0] ?? now;
          const waitMs = Math.max(0, this.windowMs - (now - oldest));
          await delay(waitMs);
          continue;
        }
        const job = this.queue.shift();
        if (!job) break;
        this.timestamps.push(Date.now());
        job();
      }
    } finally {
      this.processing = false;
    }
  }
}

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
