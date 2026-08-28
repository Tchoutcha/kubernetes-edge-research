import csv

input_file = "kourier4.txt"
output_file = "kourier1.csv"

data = []

with open(input_file, "r") as f:
    for line in f:
        line = line.strip()

        # ✅ FIX ici
        if "default.example.com" not in line:
            continue

        parts = line.split()

        try:
            status = int(parts[4])
            duration_ms = int(parts[8])
            upstream_ms = int(parts[9])

            host = parts[-2].strip('"')
            function = host.split(".")[0]

            data.append([
                function,
                status,
                duration_ms,
                upstream_ms
            ])

        except (ValueError, IndexError):
            continue

with open(output_file, "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["function", "status", "duration_ms", "upstream_ms"])
    writer.writerows(data)

print(f"{len(data)} lignes extraites → {output_file}")
