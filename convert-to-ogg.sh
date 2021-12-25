#!/bin/bash
if [[ "$#" -gt 2 || "$#" -lt 1 ]]; then
  echo "Usage: ./convert-to-ogg.sh [input WEM] [ouput OGG]"
elif [[ "$#" -eq 2 ]]; then
  ./ww2ogg "$1" -o "$2";
  ./revorb "$2";
elif [[ "$#" -eq 1 ]]; then
  ./ww2ogg "$1";
  ./revorb "${1%.*}.ogg";
fi

