package com.example.board;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.time.Instant;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.UUID;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Component;
import org.springframework.web.server.ResponseStatusException;

@Component
public class BoardStore {
    public record PostSummary(String id, String title, String createdAt, long likes) {}
    public record Comment(String id, String content, String createdAt) {}
    public record Post(String id, String title, String content, String createdAt, long likes, List<Comment> comments) {}

    private final StringRedisTemplate redis;
    private final ObjectMapper json;

    public BoardStore(StringRedisTemplate redis, ObjectMapper json) {
        this.redis = redis;
        this.json = json;
    }

    private String postKey(String id) { return "practice:board:post:" + id; }
    private String likesKey(String id) { return "practice:board:likes:" + id; }
    private String commentsKey(String id) { return "practice:board:comments:" + id; }

    public List<PostSummary> list() {
        var ids = redis.opsForZSet().reverseRange("practice:board:posts", 0, -1);
        if (ids == null) return List.of();
        return ids.stream().map(this::get).map(post ->
            new PostSummary(post.id(), post.title(), post.createdAt(), post.likes())).toList();
    }

    public Post get(String id) {
        var fields = redis.opsForHash().entries(postKey(id));
        if (fields.isEmpty()) throw new ResponseStatusException(HttpStatus.NOT_FOUND, "글을 찾을 수 없습니다.");
        var rawComments = redis.opsForList().range(commentsKey(id), 0, -1);
        var comments = rawComments == null ? List.<Comment>of() : rawComments.stream().map(value -> {
            try { return json.readValue(value, Comment.class); }
            catch (JsonProcessingException e) { throw new IllegalStateException("댓글을 읽을 수 없습니다.", e); }
        }).toList();
        var likes = redis.opsForValue().get(likesKey(id));
        return new Post(id, Objects.toString(fields.get("title")), Objects.toString(fields.get("content")),
            Objects.toString(fields.get("createdAt")), likes == null ? 0 : Long.parseLong(likes), comments);
    }

    public Post create(String title, String content) {
        var id = UUID.randomUUID().toString();
        var createdAt = Instant.now();
        redis.opsForHash().putAll(postKey(id), Map.of("title", title, "content", content,
            "createdAt", createdAt.toString()));
        redis.opsForZSet().add("practice:board:posts", id, createdAt.toEpochMilli());
        return get(id);
    }

    public Post comment(String id, String content) {
        get(id);
        var comment = new Comment(UUID.randomUUID().toString(), content, Instant.now().toString());
        try { redis.opsForList().rightPush(commentsKey(id), json.writeValueAsString(comment)); }
        catch (JsonProcessingException e) { throw new IllegalStateException("댓글을 저장할 수 없습니다.", e); }
        return get(id);
    }

    public Post like(String id) {
        get(id);
        redis.opsForValue().increment(likesKey(id));
        return get(id);
    }
}
