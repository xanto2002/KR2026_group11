## The Scenario
A bartender wants to suggest the right drinks to customers with different 
tastes and constraints, such as non-drinkers or vegans. 
The knowledge base describes drinks, their ingredients and their flavours, 
and a reasoner uses it to classify the drinks and find which ones fit each customer.

### Test customers
Some questions use test customers:
1. **Sara**: does not drink alcohol and is vegan.
2. **Marco**: drinks alcohol and likes gin.
3. **Tom**: does not drink alcohol and dislikes sweet and citrus flavours.

### Competency Questions
These are the questions the KB must be able to answer.

1. Which drinks can Sara drink? DrinkForSara Fillo
2. Which drinks fit both Marco and Sara? DrinkForMarco and DrinkForSara Fillo
3. Which drinks are vegan? VeganDrink Anto
4. Which drinks are strong (at least two different spirits)? StrongDrink Fillo
5. Which drinks have both a citrus and a bitter taste? milli
6. Is it a mistake to serve this drink to Sara? 
    (Sara doesn't drink alcohol and is vegan.) anto
7. Can a mocktail be strong?Anto
8. Which drinks would a customer who likes gin enjoy, based on the flavours of gin? Eren
9. Is there a customer for whom no drink fits? (an empty answer is interesting too) milli
10. Which non-alcoholic drink could replace a gin tonic? 
    (A drink replaces another one if it is non-alcoholic and shares its signature flavour.) Eren
