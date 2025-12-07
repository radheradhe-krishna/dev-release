package com.example.vulnerabilities;

public class UserGreeting {

    public String greetUser(String username) {
        // Vulnerable comparison: uses '==' instead of .equals()
        if (username == "admin") {
            return "Welcome back, administrator!";
        }
        return "Hello, " + username;
    }

    public boolean isGuest(String username) {
        // Another vulnerable comparison
        return username != "registeredUser";
    }
}