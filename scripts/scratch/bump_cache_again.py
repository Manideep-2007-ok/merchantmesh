
with open("frontend-v2/src/components/CatalogBotTab.jsx", "r") as f:
    content = f.read()

content = content.replace("catalog_chat_v7_", "catalog_chat_v8_")

with open("frontend-v2/src/components/CatalogBotTab.jsx", "w") as f:
    f.write(content)
