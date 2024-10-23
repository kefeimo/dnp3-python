import socket
from time import sleep


def check_port_in_use(port, host="127.0.0.1"):
    """
    # Example usage:
    port = 8080
    if check_port_in_use(port):
        print(f"Port {port} is in use.")
    else:
        print(f"Port {port} is available.")
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind((host, port))
            # If bind is successful, port is not in use
            return False
        except socket.error as e:
            # If bind fails, port is in use
            return True


class PortUnavailableError(Exception):
    pass


def get_free_port(host="127.0.0.1", start_port=20000, end_port=30000):
    """
    # Example usage:
    port = get_free_port()
    print(f"Port {port} is available.")
    """
    for port in range(start_port, end_port + 1):
        if not check_port_in_use(port, host):
            return port
        sleep(1)

    exception_msg = f"No available port found between {start_port} and {end_port}."
    raise PortUnavailableError(exception_msg)
