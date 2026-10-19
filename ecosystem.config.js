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
    {
      name: "local-companion-agent",
      cwd: ".",
      script: "python3",
      args: "scripts/local_agent.py",
      autorestart: true,
      watch: false,
    },
  ],
};
