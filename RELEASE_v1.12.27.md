## v1.12.27

### Naprawa

- **Cannot be called from within the event loop** – media source registration bez blokującego `future.result()`; użycie `add_done_callback` zamiast czekania synchronicznego
