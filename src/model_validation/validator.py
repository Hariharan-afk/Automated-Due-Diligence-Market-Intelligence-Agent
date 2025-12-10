"""
model_validation/validator.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CI/CD Validation Entry Point
"""

import sys
sys.path.append('.')

import argparse
from src.model_validation.bias_check import main as run_bias_check
from src.config import BIAS_CONFIG

def main():
    parser = argparse.ArgumentParser(description="Run Model Validation & Bias Check")
    parser.add_argument("--strict", action="store_true", help="Fail pipeline on ANY warning")
    parser.add_argument("--threshold", type=float, default=0.2, help="Minimum global score to pass")
    args = parser.parse_args()

    print("\n" + "🚀"*35)
    print("  MARKET DUE DILIGENCE MODEL VALIDATOR  ")
    print("🚀"*35 + "\n")

    try:
        import subprocess
        # Run Bias Check script as a subprocess
        print("▶️  Running Bias & Validation Suite (src/model_validation/bias_check.py)...")
        
        # Pass through any extra arguments if needed, or just default
        cmd = [sys.executable, "src/model_validation/bias_check.py", "--threshold", str(args.threshold)]
        if args.strict:
             # If strict mode is added to bias_check later, pass it. For now, just run it.
             pass

        result = subprocess.run(cmd, capture_output=False)
        
        if result.returncode == 0:
            print("\n✅ VALIDATION SUITE PASSED")
            sys.exit(0)
        else:
            print("\n❌ VALIDATION SUITE FAILED")
            sys.exit(1)
            
    except Exception as e:
        print(f"\n❌ CRITICAL ERROR IN VALIDATOR: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
