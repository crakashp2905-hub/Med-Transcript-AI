// Same-origin worklet keeps the existing script-src self policy intact.
class PCM extends AudioWorkletProcessor {
  process(inputs) {
    const channels = inputs[0];
    if (channels.length) this.port.postMessage(channels.map(channel => channel.slice()));
    return true;
  }
}
registerProcessor('scribe-pcm', PCM);
