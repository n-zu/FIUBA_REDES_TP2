# --- CONSTANTES ---

# Segundos a esperar el CONNECT de la otra parte
# de la conexión cuando se crea el socket con listener
CONNECT_WAIT_TIMEOUT = 10

# Segundos a esperar el CONNACK luego de enviar un CONNECT
# antes de reintentar enviar el CONNECT
CONNACK_WAIT_TIMEOUT = 1.5

# Segundos que espera el thread que envio el FINACK
# antes de cerrarse (durante esta espera verifica que
# no llegue otro FIN, lo que significa que no llegó el
# FINACK)
FIN_WAIT_TIMEOUT = 5

# Segundos a esperar el FINACK luego de enviar un FIN
# antes de reintentar enviar el FIN
FINACK_WAIT_TIMEOUT = 1.5

# Cantidad de reintentos a reenviar FIN o FINACK
FIN_RETRIES = 10

# Segundos a esperar el primer INFO que confirma el CONNACK
INITIAL_INFO_TIMEOUT = 5

# Cantidad de veces a reintentar enviar el CONNECT y CONNACK
# antes de fallar
CONNECT_RETRIES = 50

# Cada cuandos segundos reenviar un paquete que para el cual
# no se recibió el ACK
ACK_TIMEOUT = 1.5

# Primer numero de secuencia a enviar
INITIAL_PACKET_NUMBER = 0

# ~MTU
MAX_SIZE = 1024

# Cada cuando interrumpir el bloqueo para checkear si se esta
# cerrando el socket
STOP_CHECK_INTERVAL = 0.1

# Siempre se debe cumplir WINDOW_SIZE < ACK_NUMBERS / 2
WINDOW_SIZE = 50
ACK_NUMBERS = 4294967296

# --- CONSTANTES DE ESTADOS ---

# No envie el CONNECT (si soy socket) ni lo recibi (si soy listener)
NOT_CONNECTED = "NOT_CONNECTED"
# Soy Socket de listener, y recibi el CONNECT
CONNECTED = "CONNECTED"
# Mandé o me mandaron un FIN
CLOSING = "CLOSING"
