package com.example.vulnerabilities;

public class AuthChecker {

    private String storedPassword = "Secret123";

    public boolean isAuthenticated(String inputPassword) {
        // Vulnerable: compares references instead of values
        if (storedPassword == inputPassword) {
            return true;
        }
        return false;
    }

    public boolean hasRole(String role) {
        // Another example of the same issue
        if (role == "ADMIN") {
            return true;
        }
        return false;
    }

    public boolean isUser(String username) {
        // Yet another instance for the scanner to catch
        return username == "superuser";
    }
}