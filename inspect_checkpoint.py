import torch, os, json

CKPT = os.path.join("models", "facilityfix-ai", "pytorch_model.bin")
state = torch.load(CKPT, map_location="cpu")

cls_like = {k: list(v.shape) for k, v in state.items() if "class" in k.lower() or "head" in k.lower()}
print("Classifier-like tensors:")
for k, v in cls_like.items():
    print(f"  {k:50s} {v}")

print("\nAll top-level keys count:", len(state))
