python crop.py \
    --input_dir data \
    --output_dir cropped_data \
    --box "382 735 410 769"

These values get you to just the strip needed

python smart-width-crop-black.py \
    --input_dir cropped_data \
    --output_dir smart_cropped_data

python add-white-columns.py \
    --input_dir  smart_cropped_data \
    --output_dir final_data 

