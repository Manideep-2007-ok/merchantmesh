
with open("create_quality_seed.py", "r") as f:
    content = f.read()

target = """    # STREETWEAR
    {"id": "m3", "name": "Streetwear Hub", "category": "Clothing > Menswear"},
    {"id": "m12", "name": "Hypebeast India", "category": "Clothing > Menswear"},
    {"id": "m13", "name": "Street Style Co", "category": "Clothing > Menswear"},
    {"id": "m14", "name": "Metro Menswear", "category": "Clothing > Menswear"},
    {"id": "m15", "name": "The Hype Store", "category": "Clothing > Menswear"}
]"""

replace = """    # STREETWEAR
    {"id": "m3", "name": "Streetwear Hub", "category": "Clothing > Menswear"},
    {"id": "m12", "name": "Hypebeast India", "category": "Clothing > Menswear"},
    {"id": "m13", "name": "Street Style Co", "category": "Clothing > Menswear"},
    {"id": "m14", "name": "Metro Menswear", "category": "Clothing > Menswear"},
    {"id": "m15", "name": "The Hype Store", "category": "Clothing > Menswear"},

    # EXTRA SNEAKERS
    {"id": "m16", "name": "Sneaker Central", "category": "Footwear > Sneakers"},
    {"id": "m17", "name": "Kicksville", "category": "Footwear > Sneakers"},
    {"id": "m18", "name": "Lace Up", "category": "Footwear > Sneakers"},
    {"id": "m19", "name": "Sole Search", "category": "Footwear > Sneakers"},
    {"id": "m20", "name": "Sneaker Society", "category": "Footwear > Sneakers"},

    # EXTRA ETHNIC
    {"id": "m21", "name": "Saree Mandir", "category": "Clothing > Womenswear > Ethnic"},
    {"id": "m22", "name": "Vastra", "category": "Clothing > Womenswear > Ethnic"},
    {"id": "m23", "name": "Ethnic Charm", "category": "Clothing > Womenswear > Ethnic"},
    {"id": "m24", "name": "Indian Weaves", "category": "Clothing > Womenswear > Ethnic"},
    {"id": "m25", "name": "Silk Story", "category": "Clothing > Womenswear > Ethnic"},

    # EXTRA STREETWEAR
    {"id": "m26", "name": "Street Pulse", "category": "Clothing > Menswear"},
    {"id": "m27", "name": "Urban Drops", "category": "Clothing > Menswear"},
    {"id": "m28", "name": "Hype Central", "category": "Clothing > Menswear"},
    {"id": "m29", "name": "The Street Code", "category": "Clothing > Menswear"},
    {"id": "m30", "name": "City Fits", "category": "Clothing > Menswear"}
]"""

content = content.replace(target, replace)

with open("create_quality_seed.py", "w") as f:
    f.write(content)
print("Updated to 30 merchants!")
