import os
import json

prompt_dir = "../manifests/prompts"
manifest_dir = "../manifests/artifacts"
output_file = "../manifest_dataset.jsonl"

dataset = []

# Get list of prompt files
for filename in os.listdir(prompt_dir):
    if filename.endswith(".txt"):
        base_name = os.path.splitext(filename)[0]
        manifest_path = os.path.join(manifest_dir, f"{base_name}.properties")

        # Check if the matching manifest exists
        if os.path.exists(manifest_path):
            with open(os.path.join(prompt_dir, filename), 'r') as f_in:
                prompt_text = f_in.read().strip()

            with open(manifest_path, 'r') as f_out:
                manifest_text = f_out.read().strip()

            # Create the training sample
            sample = {
                "instruction": prompt_text,
                "output": manifest_text
            }
            dataset.append(sample)

# Save as JSONL (one JSON object per line)
with open(output_file, 'w') as f:
    for entry in dataset:
        f.write(json.dumps(entry) + '\n')

print(f"Successfully paired {len(dataset)} samples into {output_file}")