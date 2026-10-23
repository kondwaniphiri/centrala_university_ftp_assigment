// Minimal local FTP server (development/demo use)
// Usage: node server.js
// Credentials (default): user / pass  (root: ftp-roots/default)
// Exposes: control port 2121 and passive data ports 2000-2100

const { FtpSrv } = require('ftp-srv');
const path = require('path');
const fs = require('fs');

const HOST = '127.0.0.1';
const PORT = 2121;
const DATA_PORT_MIN = 2000;
const DATA_PORT_MAX = 2100;

// In‑memory demo user table (plaintext for simplicity). Swap with a real
// auth backend or hashed store for production scenarios.
const USERS = {
  user:   { password: 'pass',    root: path.resolve(__dirname, 'ftp-roots/default') },
};

// Ensure each user's root directory exists before starting the service.
Object.values(USERS).forEach(u => {
  try {
    fs.mkdirSync(u.root, { recursive: true });
  } catch (e) {
    console.error(e);
  }
});

// Instantiate ftp-srv with explicit passive port range so firewalls / local
// debugging tools are predictable.
const ftpServer = new FtpSrv({
  url: `ftp://${HOST}:${PORT}`,
  anonymous: false,
  pasv_range: [DATA_PORT_MIN, DATA_PORT_MAX],
  pasv_url: '127.0.0.1'
});

// Login event: validate credentials and supply a user-specific root.
ftpServer.on('login', ({ username, password }, resolve, reject) => {
  const user = USERS[username];
  if (!user) {
    return reject(new Error('Invalid username'));
  }
  if (password !== user.password) {
    return reject(new Error('Invalid password'));
  }
  return resolve({ root: user.root });
});

// Basic diagnostic / visibility hooks (errors & new connections).
ftpServer.on('client-error', ({ context, error }) => {
  console.error('Client error:', context, error);
});

ftpServer.on('connection', (connection) => {
  console.log(`New connection from ${connection.ip}`);
});

// Start listening and log success/failure.
ftpServer.listen()
  .then(() => {
    console.log(`FTP server running at ftp://127.0.0.1:${PORT}`);
  })
  .catch(err => {
    console.error('Failed to start FTP server:', err);
  });
