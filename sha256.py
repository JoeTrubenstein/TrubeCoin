import hashlib
m = hashlib.sha256()
m.update(b"The butterfly effect is a criminally underrated filn")
print(m.hexdigest())