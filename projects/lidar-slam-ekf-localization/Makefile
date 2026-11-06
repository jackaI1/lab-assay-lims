.PHONY: all test benchmark clean
all: build/libicp.so
build/libicp.so: cpp/icp.cpp
	mkdir -p build
	c++ -O2 -std=c++11 -shared -fPIC $< -o $@
test: all
	python -m pytest -q
benchmark: all
	python -m robot_stack.benchmark
clean:
	rm -rf build .pytest_cache
