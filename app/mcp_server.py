import math

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("MealFitnessCoachMCP")


# 1. Recipe Search Tool
@mcp.tool()
def search_recipes(query: str, dietary_tag: str | None = None) -> str:
    """Searches for healthy recipes based on a food keyword and optional dietary tag.

    Args:
        query: The food keyword (e.g. 'chicken', 'salad', 'salmon', 'potato').
        dietary_tag: Optional filter (e.g. 'vegan', 'keto', 'low-carb', 'gluten-free').
    """
    recipes = [
        {
            "name": "Quinoa & Avocado Salad",
            "tags": ["vegan", "low-carb", "gluten-free"],
            "ingredients": [
                "quinoa",
                "avocado",
                "cucumber",
                "cherry tomatoes",
                "lemon dressing",
            ],
            "instructions": "Mix cooked quinoa with chopped vegetables and avocado. Drizzle with lemon dressing.",
        },
        {
            "name": "Grilled Lemon Herb Salmon",
            "tags": ["keto", "low-carb", "gluten-free"],
            "ingredients": [
                "salmon fillet",
                "lemon",
                "rosemary",
                "olive oil",
                "garlic",
            ],
            "instructions": "Season salmon with herbs, garlic, and olive oil. Grill for 4-5 minutes on each side, serve with lemon wedges.",
        },
        {
            "name": "High-Protein Chicken Stir-Fry",
            "tags": ["low-fat", "high-protein"],
            "ingredients": [
                "chicken breast",
                "broccoli",
                "bell peppers",
                "soy sauce",
                "ginger",
                "garlic",
            ],
            "instructions": "Sauté sliced chicken with garlic and ginger. Add broccoli and peppers. Stir in soy sauce and cook until tender.",
        },
        {
            "name": "Sweet Potato & Black Bean Bowl",
            "tags": ["vegan", "gluten-free"],
            "ingredients": [
                "sweet potato",
                "black beans",
                "cilantro",
                "brown rice",
                "lime",
            ],
            "instructions": "Roast cubed sweet potatoes. Combine with warm black beans, brown rice, and top with fresh cilantro and lime.",
        },
    ]

    results = []
    for r in recipes:
        # Check query match
        query_match = query.lower() in r["name"].lower() or any(
            query.lower() in ing.lower() for ing in r["ingredients"]
        )
        # Check tag match
        tag_match = True
        if dietary_tag:
            tag_match = dietary_tag.lower() in [t.lower() for t in r["tags"]]

        if query_match and tag_match:
            results.append(r)

    if not results:
        return f"No recipes found matching query '{query}'" + (
            f" with tag '{dietary_tag}'" if dietary_tag else ""
        )

    formatted = []
    for r in results:
        formatted.append(
            f"**Recipe:** {r['name']}\n"
            f"**Tags:** {', '.join(r['tags'])}\n"
            f"**Ingredients:** {', '.join(r['ingredients'])}\n"
            f"**Instructions:** {r['instructions']}\n"
        )
    return "\n---\n".join(formatted)


# 2. Exercise Guidelines Tool
@mcp.tool()
def get_exercise_guidelines(exercise_name: str) -> str:
    """Returns safe form guidelines, tips, and target muscles for a specific exercise.

    Args:
        exercise_name: The name of the exercise (e.g. 'squat', 'bench press', 'deadlift', 'plank').
    """
    exercises = {
        "squat": {
            "target_muscles": "Quads, Glutes, Hamstrings",
            "form": "Keep your feet shoulder-width apart. Lower your hips back and down as if sitting in a chair. Keep your chest up and knees behind your toes.",
            "safety_warning": "Do not let your knees cave inward or your lower back round under load.",
        },
        "bench press": {
            "target_muscles": "Chest, Triceps, Anterior Deltoids",
            "form": "Lie flat on the bench. Grip the bar slightly wider than shoulder-width. Lower the bar to your mid-chest, then push it back up extending your arms.",
            "safety_warning": "Always use a spotter when lifting heavy. Keep your feet flat on the floor.",
        },
        "deadlift": {
            "target_muscles": "Posterior Chain (Hamstrings, Glutes, Lower Back, Traps)",
            "form": "Stand with feet mid-foot under the bar. Bend over and grab the bar. Keep your back flat, engage your core, and lift by pushing the floor away with your legs.",
            "safety_warning": "Never round your spine. Keep the bar close to your shins throughout the lift.",
        },
        "plank": {
            "target_muscles": "Core, Shoulders, Glutes",
            "form": "Rest on your forearms and toes. Keep your body in a straight line from head to heels. Engage your abs and squeeze your glutes.",
            "safety_warning": "Do not let your hips sag down or rise too high.",
        },
    }

    match = None
    for name, data in exercises.items():
        if name in exercise_name.lower() or exercise_name.lower() in name:
            match = (name, data)
            break

    if not match:
        return f"Exercise '{exercise_name}' not found. Try 'squat', 'bench press', 'deadlift', or 'plank'."

    name, data = match
    return (
        f"### Exercise Guide: {name.title()}\n"
        f"**Target Muscles:** {data['target_muscles']}\n"
        f"**Correct Form:** {data['form']}\n"
        f"**⚠️ Safety Warning:** {data['safety_warning']}"
    )


# 3. Macro and Calorie Calculator Tool
@mcp.tool()
def calculate_macros(
    weight_kg: float,
    height_cm: float,
    age: int,
    gender: str,
    activity_level: str,
    goal: str,
) -> str:
    """Calculates daily calories and macronutrient requirements (carbs, protein, fat) based on user metrics and goals.

    Args:
        weight_kg: User weight in kilograms.
        height_cm: User height in centimeters.
        age: User age in years.
        gender: User gender ('male' or 'female').
        activity_level: User activity level ('sedentary', 'light', 'moderate', 'active', 'very active').
        goal: User fitness goal ('lose weight', 'maintain weight', 'gain muscle').
    """
    # BMR calculation (Mifflin-St Jeor)
    if gender.lower() == "male":
        bmr = 10 * weight_kg + 6.25 * height_cm - 5 * age + 5
    else:
        bmr = 10 * weight_kg + 6.25 * height_cm - 5 * age - 161

    # Activity multipliers
    multipliers = {
        "sedentary": 1.2,
        "light": 1.375,
        "moderate": 1.55,
        "active": 1.725,
        "very active": 1.9,
    }

    mult = multipliers.get(activity_level.lower(), 1.2)
    tdee = bmr * mult

    # Goal adjustments
    if goal.lower() == "lose weight":
        target_calories = tdee - 500
    elif goal.lower() == "gain muscle":
        target_calories = tdee + 300
    else:
        target_calories = tdee

    # Macros split
    # Protein: 2.0g per kg (4 kcal/g)
    protein_g = weight_kg * 2.0
    protein_kcal = protein_g * 4

    # Fat: 25% of calories (9 kcal/g)
    fat_kcal = target_calories * 0.25
    fat_g = fat_kcal / 9

    # Carbs: remainder (4 kcal/g)
    carbs_kcal = target_calories - (protein_kcal + fat_kcal)
    carbs_g = carbs_kcal / 4

    return (
        f"### Caloric & Macronutrient Plan\n"
        f"- **Estimated BMR:** {math.round(bmr) if hasattr(math, 'round') else round(bmr)} kcal/day\n"
        f"- **Estimated TDEE:** {round(tdee)} kcal/day\n"
        f"- **Daily Target Calories:** {round(target_calories)} kcal/day\n"
        f"- **Macronutrient Breakdown:**\n"
        f"  * **Protein:** {round(protein_g)}g ({round(protein_kcal)} kcal, {round(protein_kcal / target_calories * 100)}%)\n"
        f"  * **Fat:** {round(fat_g)}g ({round(fat_kcal)} kcal, 25%)\n"
        f"  * **Carbohydrates:** {round(carbs_g)}g ({round(carbs_kcal)} kcal, {round(carbs_kcal / target_calories * 100)}%)"
    )


# 4. Grocery List Category Organizer Tool
@mcp.tool()
def generate_grocery_list_categories(ingredients: list[str]) -> str:
    """Groups a list of ingredients into organized supermarket categories.

    Args:
        ingredients: A list of ingredients (e.g. ['chicken breast', 'spinach', 'olive oil']).
    """
    categories = {
        "Produce": [
            "spinach",
            "lettuce",
            "avocado",
            "sweet potato",
            "broccoli",
            "bell peppers",
            "garlic",
            "ginger",
            "lime",
            "lemon",
            "cilantro",
            "cucumber",
            "cherry tomatoes",
            "tomatoes",
        ],
        "Protein": [
            "chicken",
            "salmon",
            "beef",
            "turkey",
            "eggs",
            "tofu",
            "fish",
            "pork",
        ],
        "Pantry": [
            "quinoa",
            "brown rice",
            "soy sauce",
            "olive oil",
            "black beans",
            "rosemary",
            "herbs",
            "spices",
            "oil",
            "sauce",
            "dressing",
        ],
        "Dairy": ["milk", "cheese", "yogurt", "butter", "cream"],
    }

    categorized = {cat: [] for cat in categories}
    categorized["Other"] = []

    for ing in ingredients:
        matched = False
        for cat, items in categories.items():
            if any(item in ing.lower() for item in items):
                categorized[cat].append(ing)
                matched = True
                break
        if not matched:
            categorized["Other"].append(ing)

    lines = ["### Categorized Grocery List 🛒"]
    for cat, items in categorized.items():
        if items:
            lines.append(f"**{cat}:**")
            for item in items:
                lines.append(f"  - {item}")
    return "\n".join(lines)


if __name__ == "__main__":
    mcp.run()
