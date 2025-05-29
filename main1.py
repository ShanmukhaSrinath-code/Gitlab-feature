from fastapi import FastAPI

app = FastAPI()

@app.get("/greet")
def greet(name: str = "World"):
    return {"message": f"Hello, {name}!"}
