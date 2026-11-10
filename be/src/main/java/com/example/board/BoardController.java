package com.example.board;

import java.util.List;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ResponseStatusException;

@RestController
@RequestMapping("/api/posts")
public class BoardController {
    public record TextInput(String title, String content) {}

    private final BoardStore store;

    public BoardController(BoardStore store) { this.store = store; }

    @GetMapping
    public List<BoardStore.PostSummary> list() { return store.list(); }

    @GetMapping("/{id}")
    public BoardStore.Post get(@PathVariable String id) { return store.get(id); }

    @PostMapping
    @ResponseStatus(HttpStatus.CREATED)
    public BoardStore.Post create(@RequestBody TextInput input) {
        return store.create(required(input.title(), 100), required(input.content(), 2000));
    }

    @PostMapping("/{id}/comments")
    @ResponseStatus(HttpStatus.CREATED)
    public BoardStore.Post comment(@PathVariable String id, @RequestBody TextInput input) {
        return store.comment(id, required(input.content(), 500));
    }

    @PostMapping("/{id}/likes")
    public BoardStore.Post like(@PathVariable String id) { return store.like(id); }

    private String required(String value, int maxLength) {
        if (value == null || value.isBlank() || value.length() > maxLength)
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "입력 길이를 확인해 주세요.");
        return value.trim();
    }
}
