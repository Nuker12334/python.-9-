import discord
from discord.ext import commands
import re
import base64
import ast
import operator
import os
import threading
from flask import Flask

# ------------------ Safe arithmetic evaluator ------------------
def safe_eval_math(expr: str):
    ops = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.FloorDiv: operator.floordiv,
        ast.Mod: operator.mod,
        ast.Pow: operator.pow,
        ast.USub: operator.neg,
    }
    def _eval(node):
        if isinstance(node, ast.Constant):
            return node.value
        elif isinstance(node, ast.BinOp):
            left = _eval(node.left)
            right = _eval(node.right)
            return ops[type(node.op)](left, right)
        elif isinstance(node, ast.UnaryOp):
            operand = _eval(node.operand)
            return ops[type(node.op)](operand)
        else:
            raise ValueError(f"Unsupported expression: {ast.dump(node)}")
    tree = ast.parse(expr, mode='eval')
    return _eval(tree.body)

# ------------------ WeAreDevs deobfuscation core ------------------
def deobfuscate_wearedevs(script: str) -> str:
    # Base64 decode
    def decode_base64(m):
        try:
            decoded = base64.b64decode(m.group(1)).decode('utf-8', errors='ignore')
            return f'"{decoded}"'
        except:
            return m.group(0)
    script = re.sub(r'base64\.decode\s*\(\s*["\'](.+?)["\']\s*\)', decode_base64, script, flags=re.IGNORECASE)

    # Hex decode
    def hex_to_str(m):
        try:
            chars = bytes.fromhex(m.group(1)).decode('utf-8', errors='ignore')
            return f'"{chars}"'
        except:
            return m.group(0)
    script = re.sub(r'hex\.decode\s*\(\s*["\']([0-9a-fA-F]+)["\']\s*\)', hex_to_str, script)

    # Remove loadstring wrapper
    script = re.sub(r'load(?:string)?\s*\(\s*(.+?)\s*\)', lambda m: m.group(1), script, flags=re.DOTALL)

    # Concatenation resolve (Lua ..)
    for _ in range(5):
        script = re.sub(r'(".*?"|\'.*?\')\s*\.\.\s*(".*?"|\'.*?\')',
                        lambda m: m.group(1)[:-1] + m.group(2)[1:], script)

    # Math inside string.char
    def eval_math_in_call(m):
        func = m.group(1)
        args = m.group(2)
        try:
            parts = re.split(r',\s*', args)
            evaluated = []
            for p in parts:
                p = p.strip()
                if re.match(r'^[\d\s\+\-\*\/\%\(\)]+$', p):
                    try:
                        ev = safe_eval_math(p)
                        evaluated.append(str(int(ev)) if ev == int(ev) else str(ev))
                    except:
                        evaluated.append(p)
                else:
                    evaluated.append(p)
            return f"{func}({', '.join(evaluated)})"
        except:
            return m.group(0)
    script = re.sub(r'(\w+)\s*\(\s*([^)]+)\s*\)', eval_math_in_call, script)

    # string.char conversion
    def string_char_to_str(m):
        try:
            nums = [int(x.strip()) for x in m.group(1).split(',')]
            chars = ''.join(chr(n) for n in nums)
            return f'"{chars}"'
        except:
            return m.group(0)
    script = re.sub(r'string\.char\s*\(\s*([\d,\s]+)\s*\)', string_char_to_str, script)

    # Cleanup
    script = re.sub(r'_G\[[^\]]+\]\s*=\s*function', 'function', script)
    script = re.sub(r'local\s+_ENV\s*=\s*\{.*?\}', '', script, flags=re.DOTALL)
    script = re.sub(r'\(\(\(\(', '(', script)
    script = re.sub(r'\)\)\)\)', ')', script)
    return script.strip()

# ------------------ Flask keep-alive ------------------
app = Flask('')

@app.route('/')
def health():
    return "Bot is alive"

def run_web():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = threading.Thread(target=run_web)
    t.daemon = True
    t.start()

# ------------------ Discord bot ------------------
TOKEN = os.getenv("TOKEN")
if not TOKEN:
    raise ValueError("TOKEN environment variable not set. Add it in Render environment variables.")

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix=".", intents=intents)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")

@bot.command(name="ls")
async def deobfuscate_file(ctx):
    if not ctx.message.attachments:
        await ctx.send("Please attach a Lua file (or .txt) with the obfuscated code.")
        return
    attachment = ctx.message.attachments[0]
    if not any(attachment.filename.endswith(ext) for ext in ['.lua', '.txt', '.luau']):
        await ctx.send("Unsupported file type. Please upload .lua or .txt.")
        return
    try:
        content = await attachment.read()
        script = content.decode('utf-8', errors='ignore')
    except Exception as e:
        await ctx.send(f"Failed to read file: {e}")
        return
    try:
        deobfuscated = deobfuscate_wearedevs(script)
    except Exception as e:
        await ctx.send(f"Deobfuscation error: {e}")
        return
    if not deobfuscated:
        deobfuscated = "# (Empty result – obfuscation might be unsupported)"
    file = discord.File(fp=discord.BytesIO(deobfuscated.encode('utf-8')), filename="deobfuscated.txt")
    await ctx.send("Deobfuscated code:", file=file)

# ------------------ Start both web server and bot ------------------
keep_alive()
bot.run(TOKEN)
