package collector

// Broadcaster manages SSE client connections and broadcasts snapshots
type Broadcaster struct {
	clients    map[chan []byte]struct{}
	register   chan chan []byte
	unregister chan chan []byte
	broadcast  chan []byte
	stopCh     chan struct{}
	doneCh     chan struct{}
}

// NewBroadcaster creates a new Broadcaster
func NewBroadcaster() *Broadcaster {
	return &Broadcaster{
		clients:    make(map[chan []byte]struct{}),
		register:   make(chan chan []byte),
		unregister: make(chan chan []byte),
		broadcast:  make(chan []byte, 100), // buffered to avoid blocking collector
		stopCh:     make(chan struct{}),
	}
}

// Start begins the broadcaster loop
func (b *Broadcaster) Start() {
	go func() {
		defer close(b.doneCh)
		for {
			select {
			case client := <-b.register:
				b.clients[client] = struct{}{}
			case client := <-b.unregister:
				delete(b.clients, client)
				close(client)
			case data := <-b.broadcast:
				for client := range b.clients {
					select {
					case client <- data:
					default:
						// slow client, drop and disconnect
						delete(b.clients, client)
						close(client)
					}
				}
			case <-b.stopCh:
				// cleanup all clients
				for client := range b.clients {
					close(client)
				}
				b.clients = make(map[chan []byte]struct{})
				return
			}
		}
	}()
}

// Stop gracefully stops the broadcaster
func (b *Broadcaster) Stop() {
	close(b.stopCh)
	<-b.doneCh
}

// Register adds a new client channel
func (b *Broadcaster) Register() chan []byte {
	ch := make(chan []byte, 50)
	b.register <- ch
	return ch
}

// Unregister removes a client channel
func (b *Broadcaster) Unregister(ch chan []byte) {
	b.unregister <- ch
}

// Broadcast sends data to all connected clients
func (b *Broadcaster) Broadcast(data []byte) {
	select {
	case b.broadcast <- data:
	default:
		// broadcast channel full, skip this frame
	}
}

// ClientCount returns number of connected clients
func (b *Broadcaster) ClientCount() int {
	return len(b.clients)
}