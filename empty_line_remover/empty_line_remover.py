output_lines = []
with open("serf_rtt_values_5D_with_spaces.log", "r") as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    stripped = line.lstrip()
    if stripped.startswith("==="):
        # Remove blank line before section header
        if output_lines and output_lines[-1].strip() == "":
            output_lines.pop()
        output_lines.append(stripped)
    else:
        output_lines.append(line)

with open("serf_rtt_values_5D_without_spaces.log", "w") as f:
    f.writelines(output_lines)
