import json

def parse_json_data(json_data):
    # Parse the JSON data
    data = json.loads(json_data)
    
    # Extract the layers information
    layers_info = []
    
    for layer in data['project']['clip']['layers']:
        layer_info = {
            "name": layer['name'],
            "position": layer['position'],
            "opacity": layer['opacity'],
            "start": layer['start'],
            "end": layer['end'],
            "pre-behavior": layer['pre-behavior'],
            "post-behavior": layer['post-behavior'],
            "blending-mode": layer['blending-mode']
        }
        layers_info.append(layer_info)
    
    return layers_info

# Example usage
json_data = '''
{
    "version": {
        "major": 5,
        "minor": 1
    },
    "project": {
        "format": {
            "extension": "png"
        },
        "clip": {
            "name": "Untitled",
            "width": 3372,
            "height": 2028,
            "framerate": 24.0,
            "pixelaspectratio": 1.0,
            "image-count": 9,
            "bg": {
                "red": 255,
                "green": 255,
                "blue": 255
            },
            "markin": {
                "status": false,
                "value": 0
            },
            "markout": {
                "status": false,
                "value": 0
            },
            "layers": [
                {
                    "name": "L020_Blue",
                    "visible": true,
                    "position": 0,
                    "opacity": 255,
                    "start": 2,
                    "end": 3,
                    "pre-behavior": 0,
                    "post-behavior": 1,
                    "blending-mode": "Color",
                    "group": {
                        "red": 0,
                        "green": 0,
                        "blue": 0
                    },
                    "link": [
                        {
                            "instance-index": 2,
                            "instance-name": "1",
                            "file": "L020_Blue.0003 .png",
                            "images": [
                                2
                            ]
                        },
                        {
                            "instance-index": 3,
                            "instance-name": "2",
                            "file": "L020_Blue.0004 .png",
                            "images": [
                                3
                            ]
                        }
                    ],
                    "repeat": []
                },
                {
                    "name": "L10_Pink",
                    "visible": true,
                    "position": 1,
                    "opacity": 255,
                    "start": 0,
                    "end": 8,
                    "pre-behavior": 0,
                    "post-behavior": 2,
                    "blending-mode": "Color",
                    "group": {
                        "red": 0,
                        "green": 0,
                        "blue": 0
                    },
                    "link": [
                        {
                            "instance-index": 0,
                            "instance-name": "1",
                            "file": "L10_Pink.0001 .png",
                            "images": [
                                0
                            ]
                        },
                        {
                            "instance-index": 4,
                            "instance-name": "2",
                            "file": "L10_Pink.0005 .png",
                            "images": [
                                4
                            ]
                        },
                        {
                            "instance-index": 8,
                            "instance-name": "3",
                            "file": "L10_Pink.0009 .png",
                            "images": [
                                8
                            ]
                        }
                    ],
                    "repeat": []
                }
            ]
        }
    }
}
'''

# Call the function and print(the result)
layers_info = parse_json_data(json_data)
for layer in layers_info:
    print(layer)


# Iterate through all layers and print(the opacity value)
for layer in layers_info:
    print(f"Layer Name: {layer['name']}, Opacity: {layer['opacity']}")