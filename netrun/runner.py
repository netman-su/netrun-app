import re
import netmiko


def runner(ip, device_type, credentials, commands, device_name):
    output = []

    try:
        connection = netmiko.ConnectHandler(device_type=device_type, host=ip, username=credentials[0], password=credentials[1])
        hostname = connection.find_prompt()

        if device_type == "paloalto_panos":
            hostname = re.search('@(.*)>', hostname).group(1)
        else:
            hostname = hostname.replace('#', '')

        for cmd in commands:
            output.append(connection.send_command(cmd))
            connection.find_prompt()

        connection.disconnect()

        return output, hostname

    except Exception as e:
        raise e

def guesser(ip, credentials):

 remote_device = {'device_type': 'autodetect',
                     'host': ip,
                     'username': credentials[0],
                     'password': credentials[1]}

 guesser = netmiko.SSHDetect(**remote_device)
 best_match = guesser.autodetect()

 return best_match