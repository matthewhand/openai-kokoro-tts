import torch
import os

def convert_to_onnx(pth_path, onnx_path):
    """
    Converts a PyTorch model (.pth) to ONNX format.

    Args:
        pth_path: Path to the input PyTorch model file (.pth).
        onnx_path: Path to save the output ONNX model file (.onnx).
    """

    # Ensure the directory for the ONNX file exists
    onnx_dir = os.path.dirname(onnx_path)
    if not os.path.exists(onnx_dir):
        os.makedirs(onnx_dir)

    # Load the PyTorch model
    try:
        loaded_object = torch.load(pth_path, map_location='cpu')
        print(f"Type of loaded object: {type(loaded_object)}")
        if isinstance(loaded_object, dict):
            print(f"Keys in loaded object: {loaded_object.keys()}")
            # Try to load the model architecture and weights
            model = loaded_object['bert_encoder']
            # model = loaded_object['decoder']  # Uncomment this line if 'decoder' is the correct model
            # model = loaded_object['predictor']  # Uncomment this line if 'predictor' is the correct model
        else:
            model = loaded_object

        # No need to call model.eval() here, as it's not a PyTorch model
    except Exception as e:
        print(f"Error loading PyTorch model: {e}")
        return

    # Dummy inputs for the model
    # The shapes should match the expected input of your model
    dummy_tokens = torch.randint(0, 256, (1, 100), dtype=torch.long)  # Example: batch_size=1, sequence_length=100
    dummy_style = torch.randn(1, 256)  # Example: style vector size = 256
    dummy_speed = torch.tensor([1.0], dtype=torch.float32)

    # Input names and dynamic axes
    input_names = ["tokens", "style", "speed"]
    dynamic_axes = {
        "tokens": {1: "sequence_length"},  # Example: sequence_length is dynamic
        "output": {1: "audio_length"}  # Example: audio_length is dynamic
    }
    output_names = ["output"]

    # Export the model to ONNX
    try:
        torch.onnx.export(
            model,
            (dummy_tokens, dummy_style, dummy_speed),
            onnx_path,
            input_names=input_names,
            output_names=output_names,
            dynamic_axes=dynamic_axes,
            opset_version=12,  # Choose an appropriate opset version
            verbose=True
        )
        print(f"Successfully converted model to ONNX and saved at {onnx_path}")
    except Exception as e:
        print(f"Error exporting model to ONNX: {e}")

if __name__ == "__main__":
    # Find the .pth file in the models/kokoro directory
    model_dir = os.path.join("/app", "models", "kokoro")
    pth_files = [f for f in os.listdir(model_dir) if f.endswith(".pth")]
    if not pth_files:
        print("Error: No .pth file found in the models/kokoro directory.")
        exit(1)
    pth_file_path = os.path.join(model_dir, pth_files[0])

    # Use a constant output filename "kokoro.onnx" for consistency.
    onnx_file_path = os.path.join(model_dir, "kokoro.onnx")
    convert_to_onnx(pth_file_path, onnx_file_path)