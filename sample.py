import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LogisticRegression
from sklearn.tree import DecisionTreeClassifier
from sklearn.metrics import classification_report
import joblib

# Load the dataset
df = pd.read_excel('evaluation_statistics.xlsx')

# Define feature variables and target variable
X = df[['age', 'employeecategory_id', 'yearsExperience']]
y = df['sentiment']

# Encode target variable
from sklearn.preprocessing import LabelEncoder
label_encoder = LabelEncoder()
y_encoded = label_encoder.fit_transform(y)

# Split the dataset into training and testing sets
X_train, X_test, y_train, y_test = train_test_split(X, y_encoded, test_size=0.2, random_state=42)

# Train the logistic regression model
logistic_regression_model = LogisticRegression()
logistic_regression_model.fit(X_train, y_train)

# Train the decision tree model
decision_tree_model = DecisionTreeClassifier()
decision_tree_model.fit(X_train, y_train)

# Generate predictions
y_pred_logistic = logistic_regression_model.predict(X_test)
y_pred_tree = decision_tree_model.predict(X_test)

# Generate classification reports
report_logistic = classification_report(y_test, y_pred_logistic, target_names=label_encoder.classes_, output_dict=True)
report_tree = classification_report(y_test, y_pred_tree, target_names=label_encoder.classes_, output_dict=True)

# Save models and reports
joblib.dump(logistic_regression_model, 'logistic_regression_model.pkl')
joblib.dump(decision_tree_model, 'decision_tree_model.pkl')
joblib.dump(label_encoder, 'label_encoder.pkl')
joblib.dump(report_logistic, 'logistic_regression_report.pkl')
joblib.dump(report_tree, 'decision_tree_report.pkl')

print("Logistic Regression Report:")
print(report_logistic)
print("\nDecision Tree Report:")
print(report_tree)
