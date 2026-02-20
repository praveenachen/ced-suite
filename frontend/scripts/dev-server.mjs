import net from "node:net";
import { spawn } from "node:child_process";

const START_PORT = Number(process.env.PORT || 3002);
const MAX_PORT = START_PORT + 50;

function canListenHost(port, host) {
  return new Promise((resolve) => {
    const server = net.createServer();

    server.once("error", (error) => {
      // Some environments disable IPv6; that should not block startup.
      if (error && error.code === "EAFNOSUPPORT") {
        resolve(true);
        return;
      }
      resolve(false);
    });
    server.once("listening", () => {
      server.close(() => resolve(true));
    });

    server.listen(port, host);
  });
}

async function canListen(port) {
  const [ipv4, ipv6] = await Promise.all([
    canListenHost(port, "0.0.0.0"),
    canListenHost(port, "::"),
  ]);
  return ipv4 && ipv6;
}

async function findOpenPort() {
  for (let port = START_PORT; port <= MAX_PORT; port += 1) {
    // eslint-disable-next-line no-await-in-loop
    if (await canListen(port)) return port;
  }

  throw new Error(
    `No open port found between ${START_PORT} and ${MAX_PORT}. Set PORT to another value.`
  );
}

const port = await findOpenPort();
const isFallback = port !== START_PORT;

if (isFallback) {
  console.log(
    `Port ${START_PORT} is busy, starting Next.js on ${port} instead.`
  );
}

const child = spawn("npx", ["next", "dev", "-p", String(port)], {
  stdio: "inherit",
  shell: process.platform === "win32",
});

child.on("exit", (code, signal) => {
  if (signal) process.kill(process.pid, signal);
  process.exit(code ?? 0);
});
