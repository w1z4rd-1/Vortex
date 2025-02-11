import asyncio
import openai
import sys
import json
import os

# ✅ Ensure OpenAI API key is loaded
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not OPENAI_API_KEY:
    print("[❌ ERROR] Missing OpenAI API key. Set OPENAI_API_KEY environment variable.")
    sys.exit(1)

client = openai.AsyncOpenAI(api_key=OPENAI_API_KEY)  # ✅ Use async client

async def generate_function_code(function_name, function_description):
    """Generates function code dynamically using OpenAI."""
    
    prompt = f"""
    Create a Python function named '{function_name}'. 
    - It should {function_description}.
    - Ensure the function is **fully functional** and returns **a string or a number**.
    - Always handle **errors gracefully**.
    - Example inputs: integers, strings, lists, or dictionaries.
    - The function should be **synchronous**.
    """

    try:
        response = await asyncio.wait_for(
            client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "system", "content": "You are a Python function generator."},
                          {"role": "user", "content": prompt}]
            ),
            timeout=25  # ✅ Timeout to prevent infinite waiting
        )
    except asyncio.TimeoutError:
        print("[❌ ERROR] OpenAI API request timed out.")
        return None
    except Exception as e:
        print(f"[❌ ERROR] OpenAI API failed: {e}")
        return None

    function_code = response.choices[0].message.content.strip()
    
    if not function_code:
        print("[❌ ERROR] OpenAI returned an empty function definition.")
        return None

    return function_code

async def main():
    """Main execution function to build new capabilities."""
    if len(sys.argv) < 3:
        print("[❌ ERROR] Usage: python build_capability.py <function_name> <function_description>")
        sys.exit(1)

    function_name = sys.argv[1]
    function_description = " ".join(sys.argv[2:])

    print(f"[🛠 BUILDING FUNCTION] {function_name} - {function_description}...")

    function_code = await generate_function_code(function_name, function_description)

    if function_code is None:
        print("[❌ ERROR] Failed to generate function.")
        sys.exit(1)

    # ✅ Ensure function is properly formatted
    function_code = f"\n\n# === Auto-Generated Function ===\n{function_code}\n"

    capabilities_file = "generated_capabilities.py"

    # ✅ Append function to generated_capabilities.py
    with open(capabilities_file, "a", encoding="utf-8") as f:
        f.write(function_code)

    print(f"[✅ SUCCESS] Capability '{function_name}' added. Restart VORTEX to use it.")

# ✅ Run the script asynchronously
if __name__ == "__main__":
    asyncio.run(main())
