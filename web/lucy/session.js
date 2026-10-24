// Lifecycle independent of the UI, so stop/late-connect races can be tested.
export class StudioSession {
  constructor({capture, connect, changed = () => {}}) {
    Object.assign(this, {capture, connect, changed});
    this.generation = 0; this.stream = null; this.client = null;
  }
  async start() {
    this.stop();
    const generation = this.generation;
    const stream = await this.capture();
    if (generation !== this.generation) { stream.getTracks().forEach(t => t.stop()); return false; }
    this.stream = stream;
    try {
      const client = await this.connect(stream);
      if (generation !== this.generation) { client.disconnect(); return false; }
      this.client = client;
      this.changed('connected');
      return true;
    } catch (error) {
      if (generation !== this.generation) return false;
      this.stop(); throw error;
    }
  }
  stop() {
    this.generation++;
    const client = this.client; this.client = null;
    try { Promise.resolve(client?.disconnect()).catch(() => {}); } catch {}
    this.stream?.getTracks().forEach(t => t.stop()); this.stream = null;
  }
}
