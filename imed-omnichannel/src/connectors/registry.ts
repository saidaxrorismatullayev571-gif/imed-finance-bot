import type { Connector } from './connector';

/**
 * ConnectorRegistry — channel_type -> Connector xaritasi.
 * Bir connector bir nechta type ostida ro'yxatdan o'tishi mumkin
 * (masalan Meta connector 'instagram' va 'facebook' uchun).
 */
export class ConnectorRegistry {
  private readonly byType = new Map<string, Connector>();

  register(type: string, connector: Connector): void {
    this.byType.set(type, connector);
  }

  get(type: string): Connector | undefined {
    return this.byType.get(type);
  }

  has(type: string): boolean {
    return this.byType.has(type);
  }

  types(): string[] {
    return [...this.byType.keys()];
  }
}
