# Performance dashboard for the Monster symbolic execution engine.
# Copyright (c) 2021 Computational Systems Group. All Rights Reserved.

.PHONY: build serve clean

build:
	mkdir -p target
	cp src/index.html target/index.html
	src/crit2dash.py --source=data --output=target/data.json

serve: build
	python3 -m http.server 8000 --bind 127.0.0.1 --directory target

clean:
	rm -rf target
