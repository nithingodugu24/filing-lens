export type StatusEvent = {
  type: string;
  document_id?: string;
  status?: string;
  progress?: string | null;
  page_count?: number;
};
export function connectStatus(
  onEvent: (event: StatusEvent) => void,
  onConnection: (connected: boolean) => void,
) {
  let socket: WebSocket | null = null,
    timer: ReturnType<typeof setTimeout> | undefined,
    attempt = 0,
    closed = false;
  function connect() {
    if (closed) return;
    socket = new WebSocket(
      `${location.protocol === "https:" ? "wss:" : "ws:"}//${location.host}/api/ws`,
    );
    socket.onopen = () => {
      const token = localStorage.getItem("filinglens-token");
      if (token) socket?.send(JSON.stringify({ token }));
    };
    socket.onmessage = (message) => {
      try {
        const event = JSON.parse(message.data) as StatusEvent;
        if (event.type === "ping") {
          socket?.send("pong");
          return;
        }
        if (event.type === "connected") {
          attempt = 0;
          onConnection(true);
        }
        onEvent(event);
      } catch {}
    };
    socket.onerror = () => socket?.close();
    socket.onclose = () => {
      onConnection(false);
      if (!closed)
        timer = setTimeout(
          connect,
          Math.min(30000, 1000 * 2 ** Math.min(attempt++, 5)),
        );
    };
  }
  connect();
  return () => {
    closed = true;
    if (timer) clearTimeout(timer);
    socket?.close();
  };
}
