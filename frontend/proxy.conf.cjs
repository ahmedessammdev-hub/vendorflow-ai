const port = Number(process.env.VENDORFLOW_API_PORT || '8000');
if (!Number.isInteger(port) || port < 1 || port > 65535) {
  throw new Error('VENDORFLOW_API_PORT must be a valid local TCP port.');
}

module.exports = {
  '/api/**': { target: `http://127.0.0.1:${port}` },
};
