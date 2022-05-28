SIZE = 8


def upload_to_server(socket, filename, length):
	counter = 0
	with open(filename, "wb") as file:
		while counter < length:
			data = socket.recv(SIZE)
			file.write(data)
			counter -= len(data)

	socket.close()


def download_from_server(socket, filename, length):
	with open(filename, 'r') as file:
		socket.send(file)

	socket.close() 


def check_type(socket):
	type = socket.recv(1)

	if type == 0:
		length = socket.recv(8)
		filename = socket.recv(8)
		upload_to_server(socket, filename, length)

	elif type == 1:
		length = socket.recv(8)
		filename = socket.recv(8)
		download_from_server(socket, filename, length)

	elif type == 2:
		pass
