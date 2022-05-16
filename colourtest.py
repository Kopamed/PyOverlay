base = '\033[{}m'

print("This is coloured text ")
for i in range(200):
    print(base.format(i) + "This is coloured text " + str(i))