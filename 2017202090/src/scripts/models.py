import tensorflow as tf
import numpy as np

class CNN_Encoder(tf.keras.Model):
  def __init__(self, embedding_dim):
    super(CNN_Encoder, self).__init__()
    self.fc = tf.keras.layers.Dense(embedding_dim) # convert input size to embedding_dim

  def call(self, x):
    '''
      x shape: (batch_size, 64, 2048)
    '''
    x = self.fc(x) # (batch_size, 64, embedding_dim)
    x = tf.nn.relu(x) # (batch_size, 64, embedding_dim)
    return x

class SentinelBlock(tf.keras.Model):
  def __init__(self, units):
    super(SentinelBlock, self).__init__()
    self.units = units
    self.weight_x = tf.keras.layers.Dense(units)
    self.weight_h = tf.keras.layers.Dense(units)

  def call(self, x, hidden, memory_cell):
    '''
      x shape: (batch_size, 1, embedding_dim)
      hidden shape: (batch_size, 1, units)
      memory_cell shape: (batch_size, units)
    '''

    hidden = tf.reduce_sum(hidden, axis=1) 
    x = tf.reduce_sum(x, axis=1)

    gate_t = (tf.nn.sigmoid(self.weight_x(x) +
                                         self.weight_h(hidden))) # (batch_size, units)

    state_t = gate_t * tf.nn.tanh(memory_cell)  # (batch_size, units)

    return state_t

class Attention(tf.keras.Model):
  # Adaptional Attention: visual sentinel
  def __init__(self, units):
    super(Attention, self).__init__()
    self.W_v = tf.keras.layers.Dense(units)
    self.W_g = tf.keras.layers.Dense(units)
    self.W_s = tf.keras.layers.Dense(units)
    self.V = tf.keras.layers.Dense(1)

  def call(self, features, hidden, sentinel):
    '''
      features shape: (batch_size, 64, embedding_dim)
      hidden shape: (batch_size, units)
      sentinel shape: (batch_size, units)
    '''

    sentinel = tf.expand_dims(sentinel, axis=1) # (batch_size, 1, units)

    attention_hidden_layer = (tf.nn.tanh(self.W_v(features) +
                                         self.W_g(hidden))) # (batch_size, 64, units)

    score = self.V(attention_hidden_layer) # (batch_size, 64, 1)

    attention_weights = tf.nn.softmax(score, axis=1) # (batch_size, 64, 1)

    context_vector = attention_weights * features # (batch_size, 1, embedding)
    context_vector = tf.reduce_sum(context_vector, axis=1) # (batch_size, embedding)

    # sentinel beta_t calculaltion
    score0 = self.V(tf.nn.tanh(self.W_s(sentinel) + self.W_g(hidden))) # (batch_size, 1, units)


    attention_weights_new = tf.nn.softmax(tf.concat([score0, score], axis=1), axis=1) # (batch_size, 65, 1)
    beta_t = tf.reduce_sum(attention_weights_new, axis=-1)[:,-1]

    return context_vector, attention_weights, beta_t

class RNN_Decoder(tf.keras.Model):
  def __init__(self, embedding_dim, units, vocab_size):
    super(RNN_Decoder, self).__init__()
    self.units = units
    self.embedding = tf.keras.layers.Embedding(vocab_size, embedding_dim)
    self.gru = tf.keras.layers.GRU(self.units,
                                   return_sequences=True,
                                   return_state=True,
                                   recurrent_initializer='glorot_uniform')
    self.fc1 = tf.keras.layers.Dense(self.units)
    self.fc2 = tf.keras.layers.Dense(vocab_size)

    self.attention = Attention(self.units)

    self.sentinel = SentinelBlock(self.units)


  def call(self, x, features, hidden):
    '''
      x shape: (batch_size, 1)
    '''

    # apply attention later
    # context_vector, attention_weights = self.attention(features, hidden)

    # get the word embedding presentation
    x = self.embedding(x) # ( batch_size, 1, embedding_dim)

    # alignment later
    # x = tf.concat([tf.expand_dims(context_vector, 1), x], axis=-1) # (batch_size, 1, embedding_dim + units)

    # apply GRU
    output, state = self.gru(x) # output: (batch_size, 1, units) state: batch_size, units

    # apply sentinel
    s_t = self.sentinel(x, output, state) # (batch_size, units)

    # apply attention
    context_vector, attention_weights, beta_t = self.attention(features, output, s_t) # context_vector: (batch_size, units)

    # calculate c_hat_t
    beta_t = tf.expand_dims(beta_t, axis=-1)
    context_vector_new = beta_t * s_t + (1 - beta_t) * context_vector # (batch_size, units)

    # alignment
    x = tf.concat([tf.expand_dims(context_vector_new, 1), output], axis=-1) # (batch_size, 1, units)

    x = self.fc1(output) # (batch_size, max_length, units)
    x = tf.reshape(x, (-1, x.shape[2])) # (batch_size * max_length, units)
    x = self.fc2(x) # (batch_size * max_length, vocab)

    return x, output, attention_weights

  def reset_state(self, batch_size):
    return tf.zeros((batch_size, self.units))


if __name__ == '__main__':
    encoder = CNN_Encoder(embedding_dim=256)
    decoder = RNN_Decoder(embedding_dim=256, units=256, vocab_size=2048)

    batch_size = 4

    x = np.ones([batch_size, 64, 2048])
    dec_input = tf.expand_dims([0] * batch_size, 1)

    features = encoder(x)
    hidden = decoder.reset_state(batch_size=4)
    output, hidden, _ = decoder(dec_input, features, hidden)



    