import re
import sys
import os

# Define a set of MISRA-like rules to check using regex
# In a real environment, this would be replaced by a tool like Cppcheck or LDRA.
MISRA_RULES = [
    {
        "id": "Rule 15.1",
        "description": "The 'goto' statement shall not be used.",
        "pattern": r"\bgoto\b",
        "severity": "Mandatory"
    },
    {
        "id": "Rule 21.3",
        "description": "The standard library functions malloc, calloc, realloc and free shall not be used.",
        "pattern": r"\b(malloc|calloc|realloc|free)\s*\(",
        "severity": "Mandatory"
    },
    {
        "id": "Rule 17.5",
        "description": "The function-like macro setjmp and the function longjmp shall not be used.",
        "pattern": r"\b(setjmp|longjmp)\s*\(",
        "severity": "Mandatory"
    },
    {
        "id": "Rule 4.1",
        "description": "Octal constants shall not be used.",
        "pattern": r"\b0[0-7]+\b",
        "severity": "Required"
    },
    {
        "id": "Rule 19.2",
        "description": "The union keyword shall not be used.",
        "pattern": r"\bunion\b",
        "severity": "Advisory"
    }
]

def check_file(filepath):
    violations = []
    try:
        with open(filepath, 'r') as f:
            lines = f.readlines()
            for line_num, content in enumerate(lines, 1):
                # Simple check: ignore comments (very basic)
                if content.strip().startswith("//") or content.strip().startswith("/*"):
                    continue
                
                for rule in MISRA_RULES:
                    if re.search(rule["pattern"], content):
                        violations.append({
                            "file": filepath,
                            "line": line_num,
                            "id": rule["id"],
                            "desc": rule["description"],
                            "content": content.strip()
                        })
    except Exception as e:
        print(f"Error reading {filepath}: {e}")
    return violations

def main():
    target_dirs = ["src/app", "src/bsw", "src/main.c"]
    all_violations = []
    
    print("🚀 Starting MISRA Compliance Check (Static Analysis)...")
    
    for target in target_dirs:
        if os.path.isfile(target):
            all_violations.extend(check_file(target))
        elif os.path.isdir(target):
            for root, _, files in os.walk(target):
                for file in files:
                    if file.endswith(".c") or file.endswith(".h"):
                        all_violations.extend(check_file(os.path.join(root, file)))
    
    if all_violations:
        print(f"\n❌ Found {len(all_violations)} MISRA Violations:")
        for v in all_violations:
            print(f"  - [{v['id']}] {v['file']}:{v['line']} -> {v['desc']}")
            print(f"    Code: {v['content']}")
        
        # In a professional pipeline, we might fail the build if Mandatory rules are broken
        mandatory_count = sum(1 for v in all_violations if next(r for r in MISRA_RULES if r["id"] == v["id"])["severity"] == "Mandatory")
        if mandatory_count > 0:
            print(f"\n🚨 Critical: {mandatory_count} Mandatory violations found. Failing check.")
            sys.exit(1)
    else:
        print("\n✅ No MISRA violations found in production source code.")
        sys.exit(0)

if __name__ == "__main__":
    main()
