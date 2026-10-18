module.exports = {
  apps: [
    {
      name: "remote-support-agent",
      cwd: "./tauri_agent",
      script: "npm",
      args: "run tauri dev",
      autorestart: true,
      watch: false,
      max_memory_restart: "1G",
      env: {
        NODE_ENV: "development",
      },
    },
  ],
};
