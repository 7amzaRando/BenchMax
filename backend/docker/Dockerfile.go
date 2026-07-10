# BenchMax Go sandbox — for Aider Polyglot (Go)
# No extra deps — Go stdlib is sufficient
FROM golang:1.22

WORKDIR /workspace

CMD ["go", "version"]
