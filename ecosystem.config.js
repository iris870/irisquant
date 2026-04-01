module.exports = {
  apps : [
    {
      name: 'leader',
      script: 'agents/leader.py',
      cwd: '/root/irisquant',
      interpreter: '/root/irisquant/venv/bin/python3',
      env: {
        PYTHONPATH: '.',
        LOG_LEVEL: 'info'
      },
      restart_delay: 5000
    },
    {
      name: 'news',
      script: 'agents/news.py',
      cwd: '/root/irisquant',
      interpreter: '/root/irisquant/venv/bin/python3',
      env: {
        PYTHONPATH: '.',
        LOG_LEVEL: 'info'
      },
      restart_delay: 5000
    }
  ]
};
