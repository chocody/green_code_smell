from green_code_smell import core

class ExampleClass:
    def sum(a, b):
        return a + b

    def multiply(a, b):
        return a * b
    
    def logging_example():
        import logging
        for i in range(20):
            logging.info(f"Logging iteration {i}")

    def logging_heavy():
        import logging
        logging.debug("Debug message")
        logging.info("Info message")
        logging.warning("Warning message")
        logging.error("Error message")
        logging.critical("Critical message")
        logging.info("Another info message")

code_info = core.code_info("tests/example.py")
print(code_info)