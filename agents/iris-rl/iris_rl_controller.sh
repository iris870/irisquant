#!/bin/bash
# Iris-RL Global Controller (Phase 1)
# Combines signal generation and automated evaluation/feedback loop.

VENV_PYTHON="/root/irisquant/venv/bin/python3"
GEN_SCRIPT="/root/irisquant/agents/iris-rl/signal_gen.py"
EVAL_SCRIPT="/root/irisquant/agents/iris-rl/iris_evaluator.py"
SIGNAL_FILE="/root/irisquant/outputs/ops_signals.csv"

echo "[Iris-RL] 1. Generating Signal..."
$VENV_PYTHON $GEN_SCRIPT

echo "[Iris-RL] 2. Running Automated Evaluation & Feedback..."
$VENV_PYTHON $EVAL_SCRIPT

echo "[Iris-RL] 3. Current Performance Snapshot:"
tail -n 1 $SIGNAL_FILE
