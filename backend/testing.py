
def find_alternatives(name):
    for i in name:
        if(name.index(i) % 2 != 0):
            print("Aternative strings are ", i)        
        else :
            pass
find_alternatives("Sravani")



def count_string(count_string):
    dict={}
    for i in count_string:
        keys= dict.keys()
        if i.isdigit():
            pass
        elif i in keys:
            dict[i] += 1
        else:
            dict[i] = 1
    return dict
print(count_string ("s1r3avani"))


