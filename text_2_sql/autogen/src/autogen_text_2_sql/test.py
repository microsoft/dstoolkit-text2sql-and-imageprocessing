from state_store import InMemoryStateStore

x=InMemoryStateStore()
print(x.get_state("1"))
x.save_state("1", {'x':2})
print(x.get_state("1"))