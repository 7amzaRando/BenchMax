# BenchMax Java sandbox — for Aider Polyglot (Java)
# JUnit + AssertJ pre-downloaded for offline operation
FROM eclipse-temurin:21

RUN apt-get update && apt-get install -y --no-install-recommends wget && rm -rf /var/lib/apt/lists/*

RUN mkdir -p /opt/jars && \
    wget -q https://repo1.maven.org/maven2/org/junit/platform/junit-platform-console-standalone/1.10.0/junit-platform-console-standalone-1.10.0.jar -O /opt/jars/junit.jar && \
    wget -q https://repo1.maven.org/maven2/org/assertj/assertj-core/3.25.3/assertj-core-3.25.3.jar -O /opt/jars/assertj.jar

WORKDIR /workspace

CMD ["java", "--version"]
