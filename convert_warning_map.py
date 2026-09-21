import cairosvg

input_file = "latest_warning_map.svg"
output_file = "test_warning_map.png"

print("Testing SVG rendering...")

cairosvg.svg2png(
    url=input_file,
    write_to=output_file,
    output_width=650,
    output_height=750,
    background_color="white"
)

print("Test PNG created:", output_file)